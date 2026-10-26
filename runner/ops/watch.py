"""Watch and log-tail helpers.

Extracted from runner.py.
"""
import subprocess
import time
import os
import json
import re as _re


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore


def _eventlog_tail(max_events=30, max_chars=2000, base_dir=""):
    """Recent Windows Event Log entries, for the Oracle's context.

    Windows-only. Reads System + Application (Critical/Error/Warning)
    and Security-log audit failures via wevtutil, which ships with
    Windows. Bounded. Returns None when the log cannot be read (so the
    caller says "unreadable", never "clean"); "" means it read fine and
    found nothing. Non-Windows returns None. Never raises.
    """
    R = _runner()
    if _runner().sys.platform != "win32":
        return None
    try:
        import xml.etree.ElementTree as ET
    except Exception:
        return None
    ns = "{http://schemas.microsoft.com/win/2004/08/events/event}"
    lines = []

    def _collect(xml_text):
        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return
        for ev in root.iter(ns + "Event"):
            sys_el = ev.find(ns + "System")
            if sys_el is None:
                continue
            def _t(tag, default=""):
                el = sys_el.find(ns + tag)
                return (el.text or default) if el is not None else default
            when = _t("TimeCreated")
            tc = sys_el.find(ns + "TimeCreated")
            if tc is not None:
                when = tc.get("SystemTime", "") or when
            try:
                level = R._EVENTLOG_LEVELS.get(int(_t("Level") or 4), "Info")
            except (TypeError, ValueError):
                level = "Info"
            eid = _t("EventID")
            prov = sys_el.find(ns + "Provider")
            pname = (prov.get("Name", "") if prov is not None else "") or "?"
            data_bits = []
            ed = ev.find(ns + "EventData")
            if ed is not None:
                for d in ed.iter(ns + "Data"):
                    txt = (d.text or "").strip().replace("\r", " ").replace("\n", " ")
                    if txt:
                        data_bits.append(txt)
                    if len(data_bits) >= 3:
                        break
            detail = " | ".join(data_bits)[:160]
            line = f"{when} [{level}] {pname} ({eid})"
            try:
                attack = R._EVENTLOG_ATTACK.get(int(eid))
            except (TypeError, ValueError):
                attack = None
            if attack:
                line += " [" + attack + "]"
            if detail:
                line += ": " + detail
            lines.append(line)

    level_xpath = "*[System[(Level=1 or Level=2 or Level=3)]]"
    results = [
        _runner()._wevtutil_query("System", level_xpath, 18),
        _runner()._wevtutil_query("Application", level_xpath, 8),
    ]
    audit_xpath = "*[System[(%s)]]" % " or ".join(
        "EventID=%d" % i for i in R._EVENTLOG_AUDIT_IDS)
    results.append(_runner()._wevtutil_query("Security", audit_xpath, 8))
    if all(r is None for r in results):
        return None
    for xml_text in results:
        if xml_text:
            _collect(xml_text)
    blob = "\n".join(lines[:max_events]).strip()
    if len(blob) > max_chars:
        blob = blob[-max_chars:]
    _runner()._file_fresh_lines(base_dir, "eventlog", blob)
    return blob


def _registry_watch(base_dir, max_chars=2000):
    """Windows registry watch, for the Oracle's context.

    Windows-only and read-only: enumerates autorun/persistence values
    and the service list via reg.exe, then diffs against the snapshot
    in base_dir. Reports added/changed/removed entries, bounded.
    Returns None when the registry cannot be read (so the caller says
    "unreadable", never "clean"); non-Windows returns None. Never
    raises.
    """
    R = _runner()
    if _runner().sys.platform != "win32":
        return None
    snap = _runner()._registry_snapshot()
    if snap is None:
        return None
    snap_path = ""
    if isinstance(base_dir, str) and base_dir:
        snap_path = os.path.join(base_dir, "oracle-regwatch.json")
    old = None
    if snap_path:
        try:
            with open(snap_path, encoding="utf-8") as fh:
                old = json.load(fh)
        except Exception:
            old = None
    lines = []
    if not isinstance(old, dict):
        lines.append("(baseline recorded just now; changes will show here)")
    else:
        old_keys = old.get("keys") if isinstance(old.get("keys"), dict) else {}
        changes = 0
        for key in R._REG_WATCH_KEYS:
            cur = snap["keys"].get(key, {})
            prv = old_keys.get(key, {})
            if not isinstance(prv, dict):
                prv = {}
            raw = snap["keys"].get(key + "\x00raw", {})
            tag = _runner()._reg_attack(key)
            suffix = (" [" + tag + "]") if tag else ""
            for name in sorted(set(cur) | set(prv)):
                if changes >= R._REG_WATCH_MAX_CHANGES:
                    break
                if name not in prv:
                    lines.append(f"+ {key}\\{name} = {raw.get(name, '')}{suffix}")
                    changes += 1
                elif name not in cur:
                    lines.append(f"- {key}\\{name} (removed){suffix}")
                    changes += 1
                elif cur[name] != prv[name]:
                    lines.append(f"~ {key}\\{name} (changed){suffix}")
                    changes += 1
            if changes >= R._REG_WATCH_MAX_CHANGES:
                break
        old_svc = old.get("services") if isinstance(old.get("services"), dict) else {}
        try:
            old_count = int(old_svc.get("count") or 0)
        except (TypeError, ValueError):
            old_count = 0
        new_count = snap["services"]["count"]
        if old_svc.get("hash") != snap["services"]["hash"]:
            lines.append(f"services: {old_count} -> {new_count} "
                         f"({new_count - old_count:+d}) [T1543.003]")
        if not lines:
            lines.append("(no changes since last look)")
    if snap_path:
        try:
            slim = {"saved_at": time.time(), "keys": {},
                    "services": snap["services"]}
            for key in R._REG_WATCH_KEYS:
                slim["keys"][key] = snap["keys"].get(key, {})
            _runner()._atomicio.write_json(snap_path, slim)
        except Exception:
            pass
    blob = "\n".join(lines).strip()
    if len(blob) > max_chars:
        blob = blob[:max_chars]
    if isinstance(old, dict) and isinstance(base_dir, str) and base_dir:
        _runner()._file_registry_lines(base_dir, lines)
    return blob


def _host_log_tail(max_chars=2000, base_dir="", journal=True):
    """Narrow auth and system log tail for Linux and macOS.

    File tails only. log show on macOS is a scan, so it is not used.
    journalctl is the fallback when no log file is readable, capped at
    20 error lines with a 3 second timeout. Returns None when nothing
    could be read (the caller must not say clean). "" means a log was
    read and the narrow set was empty. Windows returns None; the Event
    Log section covers that platform. Never raises.
    """
    R = _runner()
    if _runner().sys.platform == "win32":
        return None
    kept = []
    readable = False
    for path in R._AUTH_LOG_PATHS:
        rows = _runner()._tail_marked(path, R._AUTH_LOG_MARKERS)
        if rows is None:
            continue
        readable = True
        kept.extend(_runner()._label_auth(row) for row in rows)
    for path in R._SYS_LOG_PATHS:
        rows = _runner()._tail_marked(path, R._SYS_LOG_MARKERS)
        if rows is None:
            continue
        readable = True
        kept.extend(rows)
    if not readable and journal and _runner().sys.platform.startswith("linux"):
        try:
            proc = subprocess.run(
                ["journalctl", "-n", "20", "-p", "err", "--no-pager",
                 "-o", "short-iso"],
                capture_output=True, text=True, timeout=3)
        except Exception:
            proc = None
        if proc is not None and proc.returncode == 0 \
                and isinstance(proc.stdout, str):
            readable = True
            kept.extend(
                _runner()._label_auth(line.strip()[:240])
                for line in proc.stdout.splitlines() if line.strip())
    if not readable:
        return None
    blob = "\n".join(kept[-20:]).strip()
    try:
        max_chars = int(max_chars)
    except (TypeError, ValueError, OverflowError):
        max_chars = 2000
    if len(blob) > max_chars:
        blob = blob[-max_chars:]
    _runner()._file_fresh_lines(base_dir, "hostlog", blob)
    return blob


def _scrub_log_tail_lines(lines, base_dir):
    """Remove quoted material from the tail before it becomes context.

    runner.log is the debugging record and keeps everything; the
    tail that enters the Oracle's context is a different surface.
    Two kinds of quoted material must not ride it back in:

    - Model reply previews ("ask: reply '...'"). A reply can
      quote anything the model once saw -- including, in the
      Flag321 field tests, a credential value an earlier answer
      leaked, which the tail then re-imported into every later
      context. The line stays; the quote becomes a marker.
    - A flagged job's logged output: its one-line stdout preview
      and its full-output block. The retained summary withholds
      that output (see _retained_job_summary); the tail must not
      hand it back. Blocks are recognized by their header line,
      so a block whose header scrolled out of the tail window
      can still expose a fragment -- the window is bounded (last
      30 lines, capped chars), and the retained summary remains
      the withholding of record.
    """
    R = _runner()
    flagged = _runner()._flagged_job_ids(base_dir)
    out = []
    skipping = False
    for line in lines:
        if skipping:
            if line.startswith("--- end of job "):
                skipping = False
            continue
        head = R._FULL_OUTPUT_HEAD.search(line)
        if head and head.group(1) in flagged:
            skipping = True
            continue
        if R._REPLY_PREVIEW.search(line):
            line = R._REPLY_PREVIEW.sub(
                "ask: reply (preview withheld from context)", line)
        else:
            fin = R._JOB_FINISHED.search(line)
            if fin and fin.group(1) in flagged:
                line = R._STDOUT_PREVIEW.sub(
                    "stdout=(preview withheld from context)", line)
        out.append(line)
    return out


