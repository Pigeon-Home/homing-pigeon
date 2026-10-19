#!/usr/bin/env python3
"""Softflowd Feed: a Homing Pigeon user extension (example sense).

softflowd watches an interface and exports flow records as
NetFlow over UDP. There is no file to tail -- so this producer
IS the collector. Each pass it binds the listen_addr tunable
(default 127.0.0.1:2055, a loopback high port no privilege is
needed to bind), collects datagrams for collect_window_sec,
decodes them into flow dicts, and hands them to the pure
decide() as readings {"now", "flows", "skipped_records"}.
Point softflowd at it, for example:

    softflowd -i eth0 -n 127.0.0.1:2055 -v 9

It files the three signals declared in extension.json:

- flow_new_external_peer  a flow's destination is an external
                          address -- not private, loopback,
                          link-local, or multicast per the
                          ipaddress module, and not on the
                          allowlist tunable -- that state has
                          never seen before
- flow_high_volume        one flow carried at least
                          high_volume_bytes bytes
- flow_long_lived         one flow lasted at least
                          long_lived_sec from first to last

Flows are all it knows: no processes, no files, no host truth,
and no alert here claims any.

The decoder subset, stated as a boundary (the README says the
same): NetFlow v5 is decoded COMPLETE -- header plus fixed
48-byte records. NetFlow v9 is decoded from the header, the
template flowsets, and data flowsets whose records use only
the known field set below; a record carrying any other field
is skipped and counted in readings["skipped_records"].
IPFIX (version 10) gets the same treatment; a template that
carries an enterprise-specific field (the high bit, with its
private enterprise number) marks its records skipped-and-
counted, never misdecoded. Option templates, in both v9 and
IPFIX, are not decoded at all. Malformed or truncated
datagrams never raise: an incomplete record decodes to
nothing, and a datagram with a truncated header decodes to
nothing at all.

decode_datagram(data, templates=None) is the pure decoder:
one datagram in, (flows, templates) out. Templates must
persist across datagrams within a pass -- a data flowset can
arrive before its template in a later datagram -- so the
caller threads one dict through a pass and collect_flows()
starts each pass with an empty one. Across passes templates
are re-learned: softflowd re-sends them periodically, and
re-learning is correct behavior, not data loss. Two optional
arguments serve the caller: `now` is the collect time used
where a format carries no convertible timestamp (IPFIX has
no sysUpTime anchor), and `stats`, when a dict is passed,
accumulates stats["skipped_records"].

A flow dict is {"version", "src", "dst", "src_port",
"dst_port", "proto", "packets", "bytes", "first", "last"},
with first/last as epoch floats. Where the format carries
switched times (v5 First/Last, v9 FIRST/LAST_SWITCHED), they
are converted with the header's unix_secs and sysUpTime.
Where conversion is impossible, first and last both take the
collect time, so no duration is ever fabricated.

decide() is the pure shape the other examples use: readings
plus manifest plus last pass's state, out come alerts and the
new state. State remembers external peers and the flows that
already filed (once per episode: a flow files its volume and
duration signals once, keyed by its addresses, ports,
protocol, and first-seen time), both bounded by tunables with
the oldest entries evicted first. Current time arrives as
readings["now"]; decide() never reads a clock.

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload with
this sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line, and signing
and delivery follow the standard senses flow.

--readings FILE reads a readings dict from a JSON file instead
of collecting: the way to try the sense (and test it) against
known readings, on any box at all.
"""
import argparse
import ipaddress
import json
import os
import socket
import struct
import sys
import time

# The known field set, shared by NetFlow v9 field types and
# IPFIX information elements (they are one registry): a record
# using any field outside this set is skipped and counted.
_KNOWN_FIELDS = {1, 2, 4, 6, 7, 8, 11, 12, 21, 22, 27, 28}
# Fixed lengths for the known fields whose length the format
# leaves no choice about. Fields 1 (bytes) and 2 (packets) are
# counters and legitimately arrive in 1..8 octets.
_FIXED_LEN = {4: 1, 6: 1, 7: 2, 8: 4, 11: 2, 12: 4,
              21: 4, 22: 4, 27: 16, 28: 16}

_V5_HEADER = struct.Struct("!HHIIIIBBH")
_V5_RECORD = struct.Struct("!IIIHHIIIIHHBBBBHHBBH")
_V9_HEADER = struct.Struct("!HHIIII")
_IPFIX_HEADER = struct.Struct("!HHIII")
_FLOWSET_HEAD = struct.Struct("!HH")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _field_ok(ftype, flen):
    """True when one (field type, length) is in the subset."""
    if ftype not in _KNOWN_FIELDS:
        return False
    if ftype in _FIXED_LEN:
        return flen == _FIXED_LEN[ftype]
    return 1 <= flen <= 8  # the two counters, 1 and 2


def _count_skipped(stats, n=1):
    if isinstance(stats, dict):
        prev = stats.get("skipped_records")
        stats["skipped_records"] = (prev if _is_number(prev) else 0) + n


def _switched_epoch(switched_ms, uptime_ms, unix_secs):
    """A sysUpTime millisecond stamp as an epoch float.

    The header's sysUpTime is the exporter's uptime at export
    and its unix_secs is the wall clock at the same moment, so
    a stamp converts by its signed distance from sysUpTime.
    """
    return float(unix_secs) + (int(switched_ms) - int(uptime_ms)) / 1000.0


def _flow_from_values(version, values, collect_time,
                      uptime_ms=None, unix_secs=None):
    """Assemble one flow dict from {field type: raw bytes}.

    `values` holds only known fields (the caller checked).
    first/last convert from the switched stamps when the
    format anchors them (v5, v9); otherwise both fall back to
    the collect time, so the duration reads zero rather than
    something invented.
    """
    def raw(ftype):
        return values.get(ftype, b"")

    def num(ftype):
        data = raw(ftype)
        return int.from_bytes(data, "big") if data else 0

    src = ""
    dst = ""
    if raw(8):
        src = str(ipaddress.IPv4Address(raw(8)))
    elif raw(27):
        src = str(ipaddress.IPv6Address(raw(27)))
    if raw(12):
        dst = str(ipaddress.IPv4Address(raw(12)))
    elif raw(28):
        dst = str(ipaddress.IPv6Address(raw(28)))
    first = last = float(collect_time)
    if version in (5, 9) and uptime_ms is not None \
            and unix_secs is not None and (raw(21) or raw(22)):
        if raw(22):
            first = _switched_epoch(num(22), uptime_ms, unix_secs)
            last = first
        if raw(21):
            last = _switched_epoch(num(21), uptime_ms, unix_secs)
            if not raw(22):
                first = last
    return {"version": int(version), "src": src, "dst": dst,
            "src_port": num(7), "dst_port": num(11),
            "proto": num(4), "packets": num(2), "bytes": num(1),
            "first": float(first), "last": float(last)}


def _decode_records(body, fields, version, collect_time,
                    uptime_ms, unix_secs, stats):
    """Decode the data records of one flowset body.

    Every record is checked against the known set first: one
    unknown (or wrongly sized) field and the whole record is
    skipped and counted -- fields are positional, so decoding
    the rest anyway would misread every byte after it.
    Trailing bytes shorter than one record are the flowset's
    32-bit padding and are ignored.
    """
    flows = []
    rec_len = sum(flen for _ftype, flen in fields)
    if rec_len <= 0:
        return flows
    for start in range(0, len(body) - rec_len + 1, rec_len):
        record = body[start:start + rec_len]
        values = {}
        ok = True
        pos = 0
        for ftype, flen in fields:
            if not _field_ok(ftype, flen):
                ok = False
                break
            values[ftype] = record[pos:pos + flen]
            pos += flen
        if not ok:
            _count_skipped(stats)
            continue
        flows.append(_flow_from_values(
            version, values, collect_time, uptime_ms, unix_secs))
    return flows


def _decode_v5(data, collect_time):
    """NetFlow v5, complete: 24-byte header, 48-byte records."""
    if len(data) < _V5_HEADER.size:
        return []
    (_ver, count, uptime, unix_secs, _nsecs, _seq,
     _etype, _eid, _sampling) = _V5_HEADER.unpack_from(data)
    flows = []
    offset = _V5_HEADER.size
    for _i in range(count):
        if offset + _V5_RECORD.size > len(data):
            break  # truncated tail: the partial record is nothing
        fields = _V5_RECORD.unpack_from(data, offset)
        offset += _V5_RECORD.size
        values = {
            8: fields[0].to_bytes(4, "big"),
            12: fields[1].to_bytes(4, "big"),
            2: fields[5].to_bytes(8, "big"),
            1: fields[6].to_bytes(8, "big"),
            22: fields[7].to_bytes(4, "big"),
            21: fields[8].to_bytes(4, "big"),
            7: fields[9].to_bytes(2, "big"),
            11: fields[10].to_bytes(2, "big"),
            4: bytes([fields[13]]),
        }
        flows.append(_flow_from_values(
            5, values, collect_time, uptime, unix_secs))
    return flows


def _parse_v9_templates(body, key_prefix, templates):
    """Fold the template records of one template flowset in."""
    pos = 0
    while pos + 4 <= len(body):
        template_id, field_count = _FLOWSET_HEAD.unpack_from(body, pos)
        pos += 4
        fields = []
        intact = True
        for _i in range(field_count):
            if pos + 4 > len(body):
                intact = False
                break
            ftype, flen = _FLOWSET_HEAD.unpack_from(body, pos)
            pos += 4
            fields.append((ftype, flen))
        if intact:
            templates[key_prefix + (template_id,)] = {
                "fields": fields, "tainted": False}


def _parse_ipfix_templates(body, key_prefix, templates):
    """Fold the template records of one IPFIX template set in.

    A field whose element id carries the enterprise bit is
    followed by a 4-byte private enterprise number; the field
    is consumed at its true width (so the template itself
    parses), and the template is marked tainted: its data
    records are skipped and counted, never misdecoded.
    Variable-length fields (length 0xFFFF) taint it the same
    way -- records of unknown width cannot be walked at all.
    """
    pos = 0
    while pos + 4 <= len(body):
        template_id, field_count = _FLOWSET_HEAD.unpack_from(body, pos)
        pos += 4
        fields = []
        tainted = False
        intact = True
        for _i in range(field_count):
            if pos + 4 > len(body):
                intact = False
                break
            raw_type, flen = _FLOWSET_HEAD.unpack_from(body, pos)
            pos += 4
            enterprise = bool(raw_type & 0x8000)
            ftype = raw_type & 0x7FFF
            if enterprise:
                if pos + 4 > len(body):
                    intact = False
                    break
                pos += 4  # the private enterprise number itself
                tainted = True
            if flen == 0xFFFF or not _field_ok(ftype, flen):
                tainted = True
            fields.append((ftype, flen))
        if intact:
            templates[key_prefix + (template_id,)] = {
                "fields": fields, "tainted": tainted}


def _decode_templated(data, version, templates, collect_time, stats):
    """NetFlow v9 and IPFIX: header, then flowsets/sets."""
    if version == 9:
        if len(data) < _V9_HEADER.size:
            return []
        (_ver, _count, uptime, unix_secs, _seq,
         source_id) = _V9_HEADER.unpack_from(data)
        offset = _V9_HEADER.size
        limit = len(data)
    else:  # version == 10, IPFIX
        if len(data) < _IPFIX_HEADER.size:
            return []
        (_ver, total, unix_secs, _seq,
         source_id) = _IPFIX_HEADER.unpack_from(data)
        uptime = None  # IPFIX carries no sysUpTime anchor
        offset = _IPFIX_HEADER.size
        limit = min(len(data), total) if total >= _IPFIX_HEADER.size \
            else len(data)
    flows = []
    while offset + _FLOWSET_HEAD.size <= limit:
        set_id, set_len = _FLOWSET_HEAD.unpack_from(data, offset)
        if set_len < _FLOWSET_HEAD.size or offset + set_len > limit:
            break  # truncated tail: this set decodes to nothing
        body = data[offset + _FLOWSET_HEAD.size:offset + set_len]
        offset += set_len
        key_prefix = (version, source_id)
        if version == 9 and set_id == 0:
            _parse_v9_templates(body, key_prefix, templates)
        elif version == 10 and set_id == 2:
            _parse_ipfix_templates(body, key_prefix, templates)
        elif set_id >= 256:
            template = templates.get(key_prefix + (set_id,))
            if not isinstance(template, dict):
                continue  # template not seen yet this pass
            fields = template.get("fields") or []
            if template.get("tainted"):
                rec_len = sum(flen for _t, flen in fields)
                if rec_len > 0:
                    _count_skipped(stats, len(body) // rec_len)
                continue
            flows.extend(_decode_records(
                body, fields, version, collect_time,
                uptime, unix_secs, stats))
        # Template sets are handled above; option template sets
        # (v9 id 1, IPFIX id 3) and anything else are skipped
        # whole -- outside the decoded subset, by design.
    return flows


def decode_datagram(data, templates=None, now=None, stats=None):
    """One datagram -> (flows, templates). Pure; never raises.

    `templates` is the per-pass template dict: pass back what
    the last call returned. It maps (version, source id,
    template id) to the learned field layout. `now` (epoch
    float) is the collect time for flows whose format carries
    no convertible timestamp; the header's own export time
    stands in when it is absent. `stats`, when a dict, gains
    the count of records skipped for using fields outside the
    known set. Anything malformed answers with whatever
    complete records preceded the damage -- a datagram too
    short for its own header answers with nothing.
    """
    if not isinstance(templates, dict):
        templates = {}
    if not isinstance(data, (bytes, bytearray)) or len(data) < 2:
        return [], templates
    data = bytes(data)
    version = int.from_bytes(data[0:2], "big")
    collect_time = float(now) if _is_number(now) else time.time()
    try:
        if version == 5:
            return _decode_v5(data, collect_time), templates
        if version in (9, 10):
            return _decode_templated(
                data, version, templates, collect_time, stats), templates
    except (struct.error, ValueError, OverflowError):
        return [], templates
    return [], templates  # any other version is not NetFlow/IPFIX


# --- the live read: bind, listen for one window, decode -------------

def _parse_listen_addr(value):
    """'host:port' -> (host, port); anything odd -> the default."""
    host, port = "127.0.0.1", 2055
    if not isinstance(value, str) or not value.strip():
        return host, port
    text = value.strip()
    if text.startswith("[") and "]" in text:
        host = text[1:text.index("]")]
        rest = text[text.index("]") + 1:]
        if rest.startswith(":"):
            text = rest[1:]
            try:
                port = int(text)
            except ValueError:
                pass
        return (host or "127.0.0.1"), port
    if ":" in text:
        host_part, _sep, port_part = text.rpartition(":")
        if host_part:
            host = host_part
        try:
            port = int(port_part)
        except ValueError:
            pass
    else:
        host = text
    if not 0 <= port <= 65535:
        port = 2055
    return host, port


def collect_flows(manifest, state):
    """One live pass: listen for a window, decode what arrives.

    This is the live reading entry. `state` is accepted for
    the uniform producer contract and deliberately not used
    for templates: template state is per-pass by design (see
    the module docstring). A bind failure or a silent window
    is a quiet empty readings dict, never an exception --
    absence of flows is absence of evidence.
    """
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    host, port = _parse_listen_addr(tunables.get("listen_addr"))
    window = tunables.get("collect_window_sec")
    window = float(window) if _is_number(window) and window > 0 else 10.0
    max_datagrams = tunables.get("max_datagrams")
    max_datagrams = int(max_datagrams) \
        if _is_number(max_datagrams) and max_datagrams >= 1 else 1000
    try:
        family = socket.AF_INET6 \
            if ipaddress.ip_address(host).version == 6 \
            else socket.AF_INET
    except ValueError:
        family = socket.AF_INET
    readings = {"now": time.time(), "flows": [], "skipped_records": 0}
    templates = {}
    stats = {"skipped_records": 0}
    sock = None
    try:
        sock = socket.socket(family, socket.SOCK_DGRAM)
        sock.bind((host, port))
        deadline = time.monotonic() + window
        received = 0
        while received < max_datagrams:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                data, _addr = sock.recvfrom(65535)
            except OSError:
                break  # the window expired (timeout is an OSError)
            received += 1
            flows, templates = decode_datagram(
                data, templates, now=time.time(), stats=stats)
            readings["flows"].extend(flows)
    except OSError:
        pass  # cannot bind or listen: a quiet, empty pass
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
    readings["now"] = time.time()
    readings["skipped_records"] = stats["skipped_records"]
    return readings


def read_live(manifest):
    """The uniform producer entry: one live pass of collect_flows().

    Kept as a thin alias so tooling that expects every
    non-tailer example to expose read_live(manifest) finds it;
    the collector-shaped entry with its state argument is
    collect_flows() above.
    """
    return collect_flows(manifest, {})


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"peers": [], "filed": {}}


def _clean_flow(value):
    if not isinstance(value, dict):
        return None
    src = value.get("src")
    dst = value.get("dst")
    if not isinstance(src, str) or not isinstance(dst, str):
        return None
    ports = []
    for key in ("src_port", "dst_port", "proto", "packets", "bytes"):
        item = value.get(key)
        if not _is_number(item) or item < 0:
            return None
        ports.append(int(item))
    if ports[0] > 65535 or ports[1] > 65535:
        return None
    version = value.get("version")
    first = value.get("first")
    last = value.get("last")
    return {"version": int(version) if _is_number(version) else 0,
            "src": src, "dst": dst,
            "src_port": ports[0], "dst_port": ports[1],
            "proto": ports[2], "packets": ports[3], "bytes": ports[4],
            "first": float(first) if _is_number(first) else None,
            "last": float(last) if _is_number(last) else None}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    peers = state.get("peers")
    if not isinstance(peers, list):
        peers = []
    filed = state.get("filed")
    if not isinstance(filed, dict):
        filed = {}
    clean_filed = {}
    for key, when in filed.items():
        if isinstance(key, str) and _is_number(when):
            clean_filed[key] = float(when)
    return {"peers": [p for p in peers if isinstance(p, str)],
            "filed": clean_filed}


def _allowlist_networks(tunables):
    """The allowlist tunable as networks; bad entries ignored."""
    nets = []
    raw = tunables.get("allowlist")
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, str):
                continue
            try:
                nets.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                continue
    return nets


def _is_external(dst, nets):
    """True for a public destination the allowlist does not cover."""
    try:
        addr = ipaddress.ip_address(dst)
    except ValueError:
        return False
    if addr.is_private or addr.is_loopback or addr.is_link_local \
            or addr.is_multicast or addr.is_unspecified:
        return False
    return not any(addr in net for net in nets
                   if net.version == addr.version)


def _fingerprint(flow):
    """A flow's episode identity: endpoints plus its start."""
    return (f"{flow['src']}|{flow['dst']}|{flow['src_port']}|"
            f"{flow['dst_port']}|{flow['proto']}|{flow['first']}")


def _bound(mapping_or_list, limit):
    """Evict the oldest entries beyond `limit` (insertion order)."""
    if isinstance(mapping_or_list, list):
        return mapping_or_list[-limit:] if len(mapping_or_list) > limit \
            else mapping_or_list
    if len(mapping_or_list) <= limit:
        return mapping_or_list
    by_age = sorted(mapping_or_list.items(), key=lambda kv: kv[1])
    return dict(by_age[len(by_age) - limit:])


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"]. A destination files flow_new_external_peer
    the first pass state ever sees it; a flow files its
    high-volume and long-lived signals once per episode
    (its fingerprint), so replaying the same readings against
    the returned state files nothing twice. Peers and filed
    fingerprints are bounded by the max_known_peers and
    max_filed_flows tunables, oldest evicted first -- an
    evicted peer that returns files again, which is the honest
    price of a bounded memory, stated here rather than hidden.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "softflowd_feed"
    high_volume = tunables.get("high_volume_bytes")
    high_volume = int(high_volume) \
        if _is_number(high_volume) and high_volume > 0 else 50_000_000
    long_lived = tunables.get("long_lived_sec")
    long_lived = float(long_lived) \
        if _is_number(long_lived) and long_lived > 0 else 3600.0
    max_peers = tunables.get("max_known_peers")
    max_peers = int(max_peers) \
        if _is_number(max_peers) and max_peers >= 1 else 1024
    max_filed = tunables.get("max_filed_flows")
    max_filed = int(max_filed) \
        if _is_number(max_filed) and max_filed >= 1 else 1024
    nets = _allowlist_networks(tunables)

    now = readings.get("now")
    flows = []
    raw_flows = readings.get("flows")
    if isinstance(raw_flows, list):
        for entry in raw_flows:
            flow = _clean_flow(entry)
            if flow is not None:
                flows.append(flow)
    if not _is_number(now):
        now = max((f["last"] for f in flows if f["last"] is not None),
                  default=0.0)
    now = float(now)
    for flow in flows:
        if flow["first"] is None:
            flow["first"] = float(flow["last"]) \
                if flow["last"] is not None else now
        if flow["last"] is None:
            flow["last"] = float(flow["first"])

    alerts = []
    peers = list(state["peers"])
    known = set(peers)
    filed = dict(state["filed"])
    for flow in flows:
        dst = flow["dst"]
        if _is_external(dst, nets) and dst not in known:
            known.add(dst)
            peers.append(dst)
            alerts.append({
                "sensor": sensor, "signal": "flow_new_external_peer",
                "severity": "info",
                "title": f"first flow to new external peer {dst} "
                         f"(proto {flow['proto']}, "
                         f"port {flow['dst_port']})",
                "detail": {"dst": dst, "src": flow["src"],
                           "dst_port": flow["dst_port"],
                           "proto": flow["proto"]}})
        base = {"src": flow["src"], "dst": dst,
                "src_port": flow["src_port"],
                "dst_port": flow["dst_port"], "proto": flow["proto"],
                "packets": flow["packets"], "bytes": flow["bytes"]}
        fingerprint = _fingerprint(flow)
        if flow["bytes"] >= high_volume:
            key = "flow_high_volume|" + fingerprint
            if key not in filed:
                filed[key] = now
                detail = dict(base)
                detail["threshold_bytes"] = high_volume
                alerts.append({
                    "sensor": sensor, "signal": "flow_high_volume",
                    "severity": "medium",
                    "title": f"flow {flow['src']}:{flow['src_port']} "
                             f"-> {dst}:{flow['dst_port']} carried "
                             f"{flow['bytes']} bytes",
                    "detail": detail})
        duration = flow["last"] - flow["first"]
        if duration >= long_lived:
            key = "flow_long_lived|" + fingerprint
            if key not in filed:
                filed[key] = now
                detail = dict(base)
                detail["duration_sec"] = duration
                detail["first"] = flow["first"]
                detail["last"] = flow["last"]
                alerts.append({
                    "sensor": sensor, "signal": "flow_long_lived",
                    "severity": "info",
                    "title": f"flow {flow['src']}:{flow['src_port']} "
                             f"-> {dst}:{flow['dst_port']} lasted "
                             f"{duration:.0f}s",
                    "detail": detail})
    state = {"peers": _bound(peers, max_peers),
             "filed": _bound(filed, max_filed)}
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
        print(f"softflowd-feed: local delivery needs the "
              f"homing-pigeon repo importable ({e}); run me from "
              f"a clone", file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"softflowd-feed: no signing secret in "
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
            print(f"softflowd-feed: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"softflowd-feed: filed {alert.get('signal')} "
              f"via {where}", file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Softflowd Feed extension watcher: collect "
                    "NetFlow datagrams for one window and file "
                    "sensor alert payloads for new external "
                    "peers, high-volume flows, and long-lived "
                    "flows.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".softflowd-feed-state.json"),
                    help="state file (default: "
                         ".softflowd-feed-state.json next to "
                         "this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of collecting (trying the sense "
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
        print(f"softflowd-feed: cannot read manifest "
              f"{args.manifest}: {e}", file=sys.stderr)
        return 2
    state = _fresh_state()
    try:
        with open(args.state, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        pass
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"softflowd-feed: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    else:
        readings = collect_flows(manifest, state)
    alerts, state = decide(readings, manifest, state)
    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten, so
            # the next pass reports these flows again.
            print(f"softflowd-feed: {len(alerts) - delivered} of "
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
        print(f"softflowd-feed: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
