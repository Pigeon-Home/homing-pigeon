"""YARA, chat, and canary helpers.

Extracted from runner.py.
"""
import shutil
import subprocess
import tempfile
import time
import os
import sys
import json
import hashlib


from typing import Any


def _runner() -> Any:
    """The live runner module, looked up at call time.

    `runner.runner` when the suite or a package import loaded it,
    `__main__` when runner.py was started as a script (an install,
    the one-file binaries), where `runner` is the file itself and
    `from runner import runner` raises "'runner' is not a package".
    """
    for name in ("runner.runner", "__main__"):
        m = sys.modules.get(name)
        if m is not None and callable(getattr(m, "_load_mod", None)):
            return m
    from runner import runner as R  # a host that imported us first
    return R


def _yara_hits(work, targets, cfg=None):
    R = _runner()
    yr = shutil.which("yr")
    yara = shutil.which("yara")
    if not yr and not yara:
        return []
    rules_path = ""
    try:
        fd, rules_path = tempfile.mkstemp(prefix="hp-yara-", suffix=".yar")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(R._yara_rules_text(cfg))
    except OSError:
        return []
    hits = []
    deadline = time.monotonic() + 8
    try:
        for path in targets:
            if time.monotonic() > deadline:
                break
            argv = ([yr, "scan", rules_path, path] if yr
                    else [yara, rules_path, path])
            try:
                proc = subprocess.run(
                    argv, capture_output=True, text=True, timeout=5)
            except Exception:
                continue
            if not isinstance(proc.stdout, str):
                continue
            for raw in proc.stdout.splitlines():
                parts = raw.split()
                if not parts:
                    continue
                rule = parts[0]
                if rule.rstrip(":").lower() in ("error", "warning"):
                    continue
                attack = R._YARA_ATTACK.get(rule, "T1204.002")
                hits.append(
                    "yara " + rule + " " + R._rel_work(work, path)
                    + " [" + attack + "]")
    finally:
        if rules_path:
            try:
                os.remove(rules_path)
            except OSError:
                pass
    return hits


def recent_chat(base_dir, turns=None, max_chars=None):
    R = _runner()
    if turns is None:
        turns = R._CHAT_WINDOW_TURNS
    if max_chars is None:
        max_chars = R._CHAT_WINDOW_CHARS
    """The last few Oracle turns, for a continuing investigation.

    A long chat is not sent whole. The model gets the last few ask
    events, cut to max_chars. Older turns stay in oracle-chat.jsonl.
    """
    R = _runner()
    if not R._valid_base(base_dir):
        return ""
    try:
        n = int(turns)
    except (TypeError, ValueError, OverflowError):
        n = R._CHAT_WINDOW_TURNS
    if n < 1:
        return ""
    try:
        cap = int(max_chars)
    except (TypeError, ValueError, OverflowError):
        cap = R._CHAT_WINDOW_CHARS
    if cap < 1:
        return ""
    path = os.path.join(base_dir, "oracle-chat.jsonl")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return ""
    rows = []
    for line in lines:
        try:
            rec = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(rec, dict) or rec.get("event") != "ask":
            continue
        q = rec.get("question") if isinstance(rec.get("question"), str) else ""
        a = rec.get("answer") if isinstance(rec.get("answer"), str) else ""
        if not q and not a:
            continue
        rows.append((q[:300], a[:300]))
    rows = rows[-n:]
    if not rows:
        return ""
    parts = [f"You: {q}\nOracle: {a}" for q, a in rows]
    blob = "\n\n".join(parts)
    if len(blob) > cap:
        blob = blob[-cap:]
    return blob


def _canary_watch(base_dir, max_chars=2000):
    """Canary tripwire watch, for the Oracle's context.

    Cross-platform and cheap: the runner plants a few tempting-looking
    files under base_dir/canaries/, each holding a unique random token,
    and snapshots their content hashes in base_dir/canary-watch.json.
    A canary whose content changed or that went missing is TRIPPED and
    is reported by name, prominently. A trip stays reported until the
    file is restored or the snapshot is deleted: unlike the registry
    diff, the snapshot is never silently re-baselined over a trip.
    Untouched canaries collapse to one quiet line. Bounded. Returns ""
    when there is no usable base_dir; never raises.
    """
    R = _runner()
    if not R._valid_base(base_dir):
        return ""
    canary_dir = os.path.join(base_dir, "canaries")
    snap_path = os.path.join(base_dir, "canary-watch.json")
    old = None
    if not os.path.islink(snap_path):
        try:
            with open(snap_path, encoding="utf-8") as fh:
                old = json.load(fh)
        except Exception:
            old = None
    recorded = {}
    if isinstance(old, dict) and isinstance(old.get("files"), dict):
        recorded = old["files"]
    alerted = {}
    if isinstance(old, dict) and isinstance(old.get("alerted"), dict):
        alerted = dict(old["alerted"])
    first = not recorded
    try:
        os.makedirs(canary_dir, exist_ok=True)
    except OSError:
        return ""
    tripped = []
    untouched = 0
    dirty = False
    for name in R._CANARY_NAMES:
        path = os.path.join(canary_dir, name)
        if os.path.islink(path):
            tripped.append(
                "TRIPPED: canaries/%s is a symlink (not a canary) [T1552.001]"
                % name)
            if alerted.get(name) != "symlink":
                R._file_watch_alert(
                    base_dir, "canary", "high",
                    "canaries/%s is a symlink" % name,
                    "T1552.001")
                alerted[name] = "symlink"
                dirty = True
            continue
        cur = R._canary_state(path)
        rec = recorded.get(name)
        if not isinstance(rec, dict):
            # Not baselined yet: plant if missing, adopt if present.
            if cur is None:
                cur = R._plant_canary(path)
            if cur is None or cur == "?":
                continue
            recorded[name] = {"exists": True, "hash": cur}
            dirty = True
            untouched += 1
            continue
        if cur == "?":
            continue  # unreadable right now; neither a trip nor clean
        rec_hash = rec.get("hash")
        if rec.get("exists"):
            if cur is None:
                tripped.append(
                    f"TRIPPED: canaries/{name} is missing (deleted) "
                    "[T1070.004]")
                if alerted.get(name) != "deleted":
                    R._file_watch_alert(
                        base_dir, "canary", "high",
                        f"canaries/{name} is missing (deleted)",
                        "T1070.004")
                    alerted[name] = "deleted"
                    dirty = True
            elif cur != rec_hash:
                tripped.append(
                    f"TRIPPED: canaries/{name} was modified "
                    "(content changed) [T1552.001]")
                if alerted.get(name) != "modified":
                    R._file_watch_alert(
                        base_dir, "canary", "high",
                        f"canaries/{name} was modified (content changed)",
                        "T1552.001")
                    alerted[name] = "modified"
                    dirty = True
            else:
                if name in alerted:
                    alerted.pop(name, None)
                    dirty = True
                untouched += 1
        elif cur is not None:
            # Missing at baseline and present again (restored by hand):
            # adopt the new content as the baseline.
            recorded[name] = {"exists": True, "hash": cur}
            if name in alerted:
                alerted.pop(name, None)
            dirty = True
            untouched += 1
        else:
            untouched += 1
    if dirty:
        R._write_json(snap_path, {"saved_at": time.time(), "files": recorded,
                                "alerted": alerted})
    lines = []
    if first:
        lines.append(f"({len(R._CANARY_NAMES)} canaries planted just now; "
                     f"a trip will show here)")
    lines.extend(tripped)
    if untouched:
        lines.append(f"({untouched} canaries untouched)")
    blob = "\n".join(lines).strip()
    if len(blob) > max_chars:
        blob = blob[:max_chars]
    return blob


