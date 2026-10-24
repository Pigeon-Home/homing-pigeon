#!/usr/bin/env python3
"""Sysmon Feed: a Homing Pigeon user extension (example sense).

Feeds Sysmon ProcessCreate events (Event ID 1) to the Oracle.
Sysmon records every process creation with a rich, stable
field model -- image, command line, parent image, user,
hashes -- and this sense files the two shapes in that stream
that are worth waking anyone for:

- sysmon_process_from_temp  the image lives under a temp
                            directory (/tmp/, /dev/shm/,
                            /var/tmp/, a Windows per-user
                            AppData\\Local\\Temp folder, or a
                            path containing %TEMP%)
- sysmon_encoded_command    the command line carries the
                            PowerShell -enc / -encodedcommand
                            flag (case-insensitive), or a
                            base64-looking token of at least
                            100 characters from the
                            [A-Za-z0-9+/=] alphabet

Both signals are Event ID 1 only. Other Event IDs parse to
nothing in this version -- NetworkConnect, FileCreate and
the rest are future signals, not silently dropped claims;
they are simply not this sense's contract yet.

The artifact has two shapes, one field model:

- Sysmon for Linux: one event per syslog/journal line, the
  event rendered as XML text on that line
  (<Event><System><EventID>1</EventID>...</System>
  <EventData><Data Name="Image">...</Data>...</EventData>
  </Event>), possibly behind a syslog prefix.
- Windows Sysmon exported as text (wevtutil, or Event
  Viewer "Save as text"): multi-line blocks of
  "Field: value" lines with one "Event ID: 1" line per
  block, blocks separated by blank lines or by a line
  starting "Log Name:" or "Event[".

parse_event() takes ONE event's text -- either shape -- and
answers one event dict or None. The event fields are the
Event ID 1 model, normalized: event_id, utc_time,
process_guid, process_id, image, command_line,
current_directory, user, parent_process_id, parent_image,
parent_command_line, hashes.

The files are tailed incrementally, like Failed Login
Watch: main() owns the reader state -- a "_reader" sub-dict,
{path: {"inode", "offset", "partial"}} -- which decide()
preserves opaquely and ignores. read_new_events() tails from
those offsets (a missing file yields no events and keeps its
entry; an inode change or a file that shrank restarts it
from 0). The "partial" entry carries the remainder of an
event that has not terminated yet -- a half-written XML
line, or a Windows block whose separating blank line or
next block header has not arrived -- so a block is never
split across a chunk boundary.

decide() is the pure shape the other examples use: readings
plus manifest plus last pass's state, out come alerts and
the new state. An episode is (signal, image, parent_image,
rule-matched detail); an episode files once, and the filed
set is the state. Current time arrives as readings["now"];
decide() never reads a clock.

Two fixture modes feed decide() without a live Sysmon:
--readings FILE reads a readings dict ({"now", "events"})
from JSON, and --log-file FILE parses a whole fixture file
from offset 0 (flushing the final block), ignoring the
reader offsets. The fixtures under fixtures/ are SYNTHETIC:
crafted from the documented field layout, modeled on real
Sysmon output conventions. Sysmon for Linux never ran in
the environment this sense was measured in -- the host
denied BPF -- so no captured sample exists to fixture from.

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
import xml.etree.ElementTree as ET

_FIELD_NAMES = {
    "utctime": "utc_time",
    "processguid": "process_guid",
    "processid": "process_id",
    "image": "image",
    "commandline": "command_line",
    "currentdirectory": "current_directory",
    "user": "user",
    "parentprocessid": "parent_process_id",
    "parentimage": "parent_image",
    "parentcommandline": "parent_command_line",
    "hashes": "hashes",
}
_EVENT_ID_RE = re.compile(r"Event ID:\s*(\d+)")
_FIELD_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z ]*):\s+(.*)$")
_ENC_FLAG_RE = re.compile(r"-(enc|encodedcommand)\b", re.IGNORECASE)
_B64_TOKEN_RE = re.compile(r"\A[A-Za-z0-9+/=]+\Z")
_WIN_TEMP_RE = re.compile(r"^[a-z]:/users/[^/]+/appdata/local/temp/")
_TEMP_PREFIXES = ("/tmp/", "/dev/shm/", "/var/tmp/")


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


def _as_id(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return value


def _empty_event():
    return {"event_id": None, "utc_time": "", "process_guid": "",
            "process_id": "", "image": "", "command_line": "",
            "current_directory": "", "user": "",
            "parent_process_id": "", "parent_image": "",
            "parent_command_line": "", "hashes": ""}


def _finish_event(event):
    """An event dict, or None when this text is not Event ID 1."""
    if event.get("event_id") != 1:
        return None
    if not event.get("image") and not event.get("command_line"):
        return None
    return event


def _localname(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _parse_xml_event(text):
    start = text.find("<Event")
    end = text.rfind("</Event>")
    if start < 0 or end < start:
        return None
    try:
        root = ET.fromstring(text[start:end + len("</Event>")])
    except ET.ParseError:
        return None
    event = _empty_event()
    for node in root.iter():
        name = _localname(node.tag)
        if name == "EventID" and node.text:
            event["event_id"] = _as_id(node.text)
        elif name == "Data":
            field = _FIELD_NAMES.get(
                (node.get("Name") or "").replace(" ", "").lower())
            if field:
                event[field] = node.text or ""
    event["process_id"] = _as_id(event["process_id"]) \
        if event["process_id"] != "" else ""
    event["parent_process_id"] = _as_id(event["parent_process_id"]) \
        if event["parent_process_id"] != "" else ""
    return _finish_event(event)


def _parse_text_event(text):
    m = _EVENT_ID_RE.search(text)
    if not m:
        return None
    event = _empty_event()
    event["event_id"] = int(m.group(1))
    for line in text.splitlines():
        fm = _FIELD_LINE_RE.match(line.strip())
        if not fm:
            continue
        field = _FIELD_NAMES.get(
            fm.group(1).replace(" ", "").lower())
        if field:
            event[field] = fm.group(2).strip()
    event["process_id"] = _as_id(event["process_id"]) \
        if event["process_id"] != "" else ""
    event["parent_process_id"] = _as_id(event["parent_process_id"]) \
        if event["parent_process_id"] != "" else ""
    return _finish_event(event)


def parse_event(text):
    """One event's text (either shape) -> one event dict, or None.

    Event ID 1 only: any other Event ID, malformed XML, a
    text block with no "Event ID:" line, and anything that is
    not a Sysmon event at all answer None.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    if "<Event" in text:
        return _parse_xml_event(text)
    return _parse_text_event(text)


# --- reading: tail from saved offsets, never split a block -----------

def _split_text(buf, flush=False):
    """Split a buffer into complete event texts.

    Returns (texts, remainder). XML events are one per line:
    a trailing line with no newline yet is the remainder.
    Windows text blocks end at a blank line or at the next
    block's header line ("Log Name:" / "Event["); the
    trailing, unterminated block is the remainder. With
    flush=True (whole-file fixture mode) the remainder is
    returned as a final text instead.
    """
    if "<Event" in buf:
        if flush:
            return [ln for ln in buf.splitlines() if ln.strip()], ""
        if buf.endswith("\n"):
            return buf.splitlines(), ""
        parts = buf.split("\n")
        return parts[:-1], parts[-1]
    blocks = []
    current = []
    for line in buf.splitlines():
        is_header = line.startswith("Log Name:") \
            or line.startswith("Event[")
        if is_header and current:
            blocks.append("\n".join(current))
            current = [line]
            continue
        if not line.strip():
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if flush:
        if current:
            blocks.append("\n".join(current))
        return blocks, ""
    remainder = "\n".join(current)
    if current and buf.endswith("\n"):
        # The block's last line is complete even though the
        # block is not: keep its newline, so the next chunk's
        # first line does not glue onto it.
        remainder += "\n"
    return blocks, remainder


def read_new_events(paths, reader_state):
    """Tail each path from its saved offset.

    Returns (events, new_reader_state). A missing or
    unreadable file yields no events and keeps its previous
    entry (offset and partial block alike); an inode change
    or a file smaller than its saved offset restarts that
    file from 0 with no carried partial. The reader entry is
    {"inode", "offset", "partial"}: offset advances past
    everything read, and "partial" carries the unterminated
    remainder the next pass prepends before splitting.
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
        have_prev = isinstance(prev_inode, int) \
            and not isinstance(prev_inode, bool) \
            and isinstance(prev_offset, int) \
            and not isinstance(prev_offset, bool) and prev_offset >= 0
        prev_partial = prev.get("partial") \
            if isinstance(prev, dict) else ""
        if not isinstance(prev_partial, str):
            prev_partial = ""
        try:
            st = os.stat(path)
        except OSError:
            if have_prev:
                new_reader[path] = {"inode": prev_inode,
                                    "offset": prev_offset,
                                    "partial": prev_partial}
            continue
        restart = not have_prev or prev_inode != st.st_ino \
            or prev_offset > st.st_size
        offset = 0 if restart else prev_offset
        carried = "" if restart else prev_partial
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                fh.seek(offset)
                data = fh.read()
                new_offset = fh.tell()
        except OSError:
            if have_prev:
                new_reader[path] = {"inode": prev_inode,
                                    "offset": prev_offset,
                                    "partial": prev_partial}
            continue
        texts, remainder = _split_text(carried + data)
        for text in texts:
            event = parse_event(text)
            if event is not None:
                events.append(event)
        new_reader[path] = {"inode": st.st_ino, "offset": new_offset,
                            "partial": remainder}
    return events, new_reader


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"filed": {}}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    filed = state.get("filed")
    if not isinstance(filed, dict):
        filed = {}
    out = {"filed": {k: True for k in filed if isinstance(k, str)}}
    reader = state.get("_reader")
    if isinstance(reader, dict):
        out["_reader"] = reader
    return out


def _temp_match(image):
    """The temp marker an image path matches, or None."""
    if not isinstance(image, str) or not image:
        return None
    low = image.lower()
    if "%temp%" in low:
        return "%TEMP%"
    slashed = low.replace("\\", "/")
    for prefix in _TEMP_PREFIXES:
        if slashed.startswith(prefix):
            return prefix
    m = _WIN_TEMP_RE.match(slashed)
    if m:
        return m.group(0)
    return None


def _encoded_match(command_line):
    """The encoded-command marker a command line carries, or None.

    The -enc / -encodedcommand flag wins when present;
    otherwise the first whitespace-separated token of at
    least 100 characters drawn only from the base64
    alphabet is the marker.
    """
    if not isinstance(command_line, str) or not command_line:
        return None
    m = _ENC_FLAG_RE.search(command_line)
    if m:
        return "-" + m.group(1).lower()
    for token in command_line.split():
        token = token.strip("\"'")
        if len(token) >= 100 and _B64_TOKEN_RE.match(token):
            return token
    return None


def _clean_events(readings):
    events = []
    raw = readings.get("events") if isinstance(readings, dict) else None
    if not isinstance(raw, list):
        return events
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        event_id = entry.get("event_id")
        if event_id is not None and event_id != 1:
            continue
        image = entry.get("image")
        command = entry.get("command_line")
        if not isinstance(image, str):
            image = ""
        if not isinstance(command, str):
            command = ""
        if not image and not command:
            continue
        parent = entry.get("parent_image")
        user = entry.get("user")
        events.append({
            "image": image, "command_line": command,
            "parent_image": parent if isinstance(parent, str) else "",
            "user": user if isinstance(user, str) else ""})
    return events


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock. Each Event ID 1 event is tested
    against both rules; a matching rule files its signal
    unless that episode -- (signal, image, parent_image,
    rule-matched detail) -- is already in the filed set the
    state carries. The rule-matched detail is the image for
    the temp rule (the temp path is the finding) and the
    command line for the encoded rule (a different encoded
    command is a different episode).
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "sysmon_feed"
    alerts = []
    for event in _clean_events(readings):
        image = event["image"]
        parent = event["parent_image"]
        checks = []
        marker = _temp_match(image)
        if marker is not None:
            checks.append(("sysmon_process_from_temp", marker, image))
        marker = _encoded_match(event["command_line"])
        if marker is not None:
            checks.append(("sysmon_encoded_command", marker,
                           event["command_line"]))
        for signal, marker, detail_key in checks:
            key = json.dumps([signal, image, parent, detail_key],
                             sort_keys=True)
            if key in state["filed"]:
                continue
            state["filed"][key] = True
            if signal == "sysmon_process_from_temp":
                title = f"process from temp location: {image}"
            else:
                title = f"encoded command line from {image or '?'}"
            alerts.append({
                "sensor": sensor, "signal": signal,
                "severity": "medium", "title": title,
                "detail": {"image": image, "parent_image": parent,
                           "command_line": event["command_line"],
                           "user": event["user"],
                           "matched": marker}})
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
        print(f"sysmon-feed: local delivery needs the "
              f"homing-pigeon repo importable ({e}); run me from "
              f"a clone", file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"sysmon-feed: no signing secret in "
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
            print(f"sysmon-feed: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"sysmon-feed: filed {alert.get('signal')} "
              f"via {where}", file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Sysmon Feed extension watcher: tail the "
                    "Sysmon event text once and file sensor "
                    "alert payloads for Event ID 1 processes "
                    "from temp locations and encoded command "
                    "lines.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".sysmon-feed-state.json"),
                    help="state file (default: "
                         ".sysmon-feed-state.json next to "
                         "this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the event text (trying the "
                         "sense against known readings, on any box)")
    ap.add_argument("--log-file", default=None,
                    help="parse this whole file from offset 0 "
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
        print(f"sysmon-feed: cannot read manifest "
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
            print(f"sysmon-feed: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    elif args.log_file:
        try:
            with open(args.log_file, encoding="utf-8",
                      errors="replace") as fh:
                content = fh.read()
        except OSError as e:
            print(f"sysmon-feed: cannot read log file "
                  f"{args.log_file}: {e}", file=sys.stderr)
            return 2
        texts, _rem = _split_text(content, flush=True)
        events = [ev for ev in (parse_event(t) for t in texts)
                  if ev is not None]
        readings = {"now": time.time(), "events": events}
    else:
        paths = tunables.get("log_paths")
        if not isinstance(paths, list) or not paths:
            paths = ["/var/log/syslog", "/var/log/messages"]
        reader = state.get("_reader") if isinstance(state, dict) else None
        events, new_reader = read_new_events(paths, reader or {})
        readings = {"now": time.time(), "events": events}
    alerts, state = decide(readings, manifest, state)
    if new_reader is not None:
        state["_reader"] = new_reader
    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten, so
            # the offsets do not advance and the next pass
            # re-reads these events.
            print(f"sysmon-feed: {len(alerts) - delivered} of "
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
        print(f"sysmon-feed: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
