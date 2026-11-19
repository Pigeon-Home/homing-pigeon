#!/usr/bin/env python3
"""Built-in resource monitor. On by default.

Stdlib-only sampling of CPU, memory, and disk pressure. Linux reads
/proc/stat and /proc/meminfo; disk uses shutil.disk_usage, which
works everywhere; other platforms degrade gracefully to disk-only.

When a resource crosses the configured threshold, check_resources()
returns an event dict (and records a per-resource cooldown so a
sustained overload pages once, not every poll). The caller appends
the event to security-events.jsonl, where the DRI trigger
evaluation picks it up. The monitor itself never pages — it records.

This is the built-in half of the telemetry story: cheap, always on,
no daemon. The extension senses (host IDS, netmon, sysmon) are the
other half.

The same module carries the disk guard (guard_disk, below): the
acting half of the disk story. The monitor records pressure; the
guard, on by default, keeps the runner's own material from filling
the host disk past 90%.
"""
import json
import os
import shutil
import stat
import threading
import time

try:
    from runner.guard import atomicio as _atomicio
except ImportError:
    from guard import atomicio as _atomicio  # type: ignore
try:
    from runner.guard import confval as _confval
except ImportError:
    from guard import confval as _confval  # type: ignore
from datetime import datetime, timezone

STATE_FILE = "resources.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_resources(cfg) -> dict:
    """Validate cfg["resources"]. On by default. Raises RuntimeError."""
    if not isinstance(cfg, dict):
        raise RuntimeError("config error: config must be an object")
    raw = cfg.get("resources")
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise RuntimeError("config error: resources must be an object")
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        raise RuntimeError("config error: resources.enabled must be a boolean")
    # Every malformed value here is a startup config error, the
    # documented posture for this block: a boolean (true once read
    # as threshold 1.0 and cooldown 1), and a number too large for
    # a float (once a raw OverflowError out of the reader) included.
    threshold = _confval.number(raw.get("threshold", 0.95), None)
    if threshold is None:
        raise RuntimeError("config error: resources.threshold must be a number")
    threshold = float(threshold)
    if not 0 < threshold <= 1:
        raise RuntimeError("config error: resources.threshold must be in (0, 1]")
    raw_cooldown = raw.get("cooldown_sec", 900)
    cooldown = _confval.number(raw_cooldown, None)
    if cooldown is None:
        if isinstance(raw_cooldown, float) or (
                isinstance(raw_cooldown, int)
                and not isinstance(raw_cooldown, bool)):
            # A number, but not a usable one: infinity, NaN, or an
            # integer too large for a float.
            raise RuntimeError("config error: resources.cooldown_sec "
                               "must be a finite number >= 0")
        raise RuntimeError("config error: resources.cooldown_sec must be a number")
    cooldown = float(cooldown)
    if cooldown < 0:
        raise RuntimeError(
            "config error: resources.cooldown_sec must be a finite number >= 0")
    return {"enabled": enabled, "threshold": threshold,
            "cooldown_sec": cooldown}


def _read_proc_stat():
    """Return (idle, total) jiffies, or None off Linux."""
    try:
        with open("/proc/stat", "r") as f:
            parts = f.readline().split()
        if not parts or parts[0] != "cpu":
            return None
        nums = [int(x) for x in parts[1:]]
        idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
        return idle, sum(nums)
    except (OSError, ValueError, IndexError):
        return None


def _cpu_percent(prev, cur):
    if not isinstance(prev, (list, tuple)) or not isinstance(cur, (list, tuple)):
        return None
    if len(prev) < 2 or len(cur) < 2:
        return None
    try:
        idle_d = float(cur[0]) - float(prev[0])
        total_d = float(cur[1]) - float(prev[1])
    except (TypeError, ValueError):
        return None
    if total_d <= 0:
        return None
    return max(0.0, min(1.0, 1.0 - idle_d / total_d))


def _mem_fraction():
    """Fraction of memory used, or None off Linux."""
    try:
        info = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                k, _, v = line.partition(":")
                info[k.strip()] = int(v.strip().split()[0])
        total = info.get("MemTotal")
        avail = info.get("MemAvailable", info.get("MemFree"))
        if not total or not avail:
            return None
        return max(0.0, min(1.0, 1.0 - avail / total))
    except (OSError, ValueError, IndexError):
        return None


def _disk_fraction(path):
    if not isinstance(path, (str, bytes, os.PathLike)):
        return None
    try:
        u = shutil.disk_usage(path)
        if u.total <= 0:
            return None
        return max(0.0, min(1.0, u.used / u.total))
    except (OSError, TypeError, ValueError, ZeroDivisionError):
        return None


def _load_state(base_dir):
    if not isinstance(base_dir, str) or not base_dir:
        return {}
    path = os.path.join(base_dir, STATE_FILE)
    if os.path.islink(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            st = json.load(f)
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


_STATE_LOCK = threading.Lock()


def _save_state(base_dir, state):
    if not isinstance(base_dir, str) or not base_dir:
        return
    if not isinstance(state, dict):
        state = {}
    # A set, a bad key, or a value whose text form raises must not
    # stop the sample. Drop what cannot be stored. Keep the rest.
    clean = {}
    for k, v in state.items():
        try:
            key = k if isinstance(k, str) else str(k)
        except Exception:
            continue
        try:
            json.dumps(v)
            clean[key] = v
        except (TypeError, ValueError):
            try:
                clean[key] = str(v)
            except Exception:
                continue
    path = os.path.join(base_dir, STATE_FILE)
    try:
        with _STATE_LOCK:
            _atomicio.write_json(path, clean)
    except (OSError, TypeError, ValueError):
        pass


def check_resources(cfg, base_dir, now=None):
    """Sample resources. Returns an event dict when a threshold is
    crossed (per-resource cooldown), else None. Always updates state
    so CPU has a baseline next cycle."""
    try:
        now = float(time.time() if now is None else now)
    except (TypeError, ValueError):
        now = time.time()
    if not isinstance(cfg, dict) or not isinstance(base_dir, str):
        return None
    try:
        rcfg = parse_resources(cfg)
    except (RuntimeError, AttributeError, TypeError):
        return None
    if not rcfg["enabled"]:
        return None
    state = _load_state(base_dir)

    cur_cpu = _read_proc_stat()
    cpu = _cpu_percent(state.get("cpu_prev"), cur_cpu)
    mem = _mem_fraction()
    disk = _disk_fraction(base_dir)

    state["cpu_prev"] = list(cur_cpu) if cur_cpu else state.get("cpu_prev")
    state["checked_at"] = _now_iso()

    threshold = rcfg["threshold"]
    cooldown = rcfg["cooldown_sec"]
    last_alert = state.get("last_alert") or {}
    if not isinstance(last_alert, dict):
        last_alert = {}
    over = {}
    for name, val in (("cpu", cpu), ("mem", mem), ("disk", disk)):
        if val is None or val < threshold:
            continue
        try:
            last = float(last_alert.get(name, 0) or 0)
        except (TypeError, ValueError):
            last = 0.0
        if now - last >= cooldown:
            over[name] = round(val, 4)
            last_alert[name] = now
    state["last_alert"] = last_alert
    _save_state(base_dir, state)

    if not over:
        return None
    return {
        "type": "resource_pressure",
        "at": _now_iso(),
        "threshold": threshold,
        "resources": over,
    }


# ------------------------------------------------------------ disk guard
# The 90% disk truncation guard. On by default: a plain install,
# with no setting changed, keeps the runner from letting its own
# material fill the host disk past 90%. The guard acts only on the
# runner's own material under base_dir: its logs first (rolled
# backups, then the oldest lines of the live logs), then recorded
# results and retained outputs, oldest first, then given up result
# stashes, then job workspaces no job can still be running in. A
# recorded result a redelivery could still ask for stays: one no
# older than the freshness window and its future bound. It
# never touches anything outside base_dir, and it never stops the
# runner: it stops the growth, records what it did, and the poll
# carries on. The one opt out is the top level setting
# no_90_disk_truncation; only a literal true turns the guard off.
#
# security-events.jsonl is not truncated: it caps itself at append
# time, and it is where the guard's own annotation lands.

DISK_GUARD_THRESHOLD = 0.90
DISK_GUARD_LOG_KEEP_BYTES = 65536
DISK_GUARD_WORK_MIN_AGE_SEC = 3600
DISK_GUARD_MAX_ACTIONS = 512
_DISK_GUARD_LOG_NAMES = ("runner.log", "oracle.log", "oracle-chat.jsonl")
_DISK_GUARD_OLD_DIRS = ("sent", "retained", os.path.join("outbox", "failed"))
# The door takes a job dated up to this far ahead of the clock
# (the freshness check in runner/ops/mail.py).
DISK_GUARD_REPLAY_SKEW_SEC = 300


def disk_guard_enabled(cfg) -> bool:
    """True unless cfg turns the guard off with a literal true.

    The reading mirrors the setup wizard's autogen_login: the safe
    behaviour is the default, and only the exact opt out value
    changes it. An absent key, false, or an unusable value all
    leave the guard on.
    """
    if not isinstance(cfg, dict):
        return True
    return cfg.get("no_90_disk_truncation") is not True


def _guard_size(path):
    """Size of a regular file, or None for anything else. A
    symlink is never followed."""
    try:
        st = os.lstat(path)
    except OSError:
        return None
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return None
    return st.st_size


def _guard_truncate_log(path, keep):
    """Drop the oldest lines of one log file, keeping its newest
    keep bytes, aligned forward to a line boundary. Returns the
    bytes freed, or 0 when nothing was freed. The file is rewritten
    in place, so a writer holding it open in append mode keeps
    appending to the same file. A symlink is never followed."""
    size = _guard_size(path)
    if size is None or size <= keep:
        return 0
    try:
        with open(path, "rb") as f:
            f.seek(size - keep)
            tail = f.read()
    except OSError:
        return 0
    nl = tail.find(b"\n")
    if 0 <= nl < len(tail) - 1:
        tail = tail[nl + 1:]
    try:
        with open(path, "r+b") as f:
            f.write(tail)
            f.truncate(len(tail))
    except OSError:
        return 0
    return size - len(tail)


def _guard_oldest_files(d):
    """(mtime, path, size) for the regular files directly in d,
    oldest first. Symlinks and subdirectories are skipped."""
    out = []
    try:
        names = os.listdir(d)
    except OSError:
        return out
    for name in names:
        path = os.path.join(d, name)
        try:
            st = os.lstat(path)
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            continue
        out.append((st.st_mtime, path, st.st_size))
    out.sort()
    return out


def _guard_replay_window(cfg):
    """Seconds for which a recorded result can still be asked
    for by a redelivery the door would take: the freshness
    window, max_job_age_sec, and its future bound. A record in
    sent/ no older than this is the layer that answers a
    redelivery once the replay cache has let the id go, so the
    guard does not give it up: the job would run again."""
    raw = cfg.get("max_job_age_sec") if isinstance(cfg, dict) else None
    return _confval.integer(raw, 3600, lo=1) + DISK_GUARD_REPLAY_SKEW_SEC


def _guard_remove_file(path):
    """Remove one file. Returns the bytes freed, 0 for an empty
    file, or None when nothing was removed: a removal is an
    action whatever it freed."""
    size = _guard_size(path)
    if size is None:
        return None
    try:
        os.remove(path)
    except OSError:
        return None
    return size


def _guard_tree_bytes(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                continue
    return total


def _guard_oldest_workspaces(base_dir, now):
    """(mtime, path, bytes) for leftover job workspaces old enough
    that no job can still be running in them, oldest first. A job
    runs at most 3600 seconds, so a workspace untouched for longer
    than that is a leftover, not a live one."""
    root = os.path.join(base_dir, "work")
    out = []
    try:
        names = os.listdir(root)
    except OSError:
        return out
    for name in names:
        path = os.path.join(root, name)
        try:
            st = os.lstat(path)
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            continue
        if now - st.st_mtime < DISK_GUARD_WORK_MIN_AGE_SEC:
            continue
        out.append((st.st_mtime, path, _guard_tree_bytes(path)))
    out.sort()
    return out


def _guard_tree_entries(path):
    return sum(len(dirs) + len(files)
               for _root, dirs, files in os.walk(path))


def _guard_remove_tree(path):
    """Remove one workspace. Returns the bytes freed, 0 for an
    empty one, or None when it stands as it stood. A removal
    that stopped part way freed what it freed, and is an action
    too."""
    size = _guard_tree_bytes(path)
    held = _guard_tree_entries(path)
    try:
        shutil.rmtree(path)
    except OSError:
        pass
    if not os.path.lexists(path):
        return size
    if _guard_tree_entries(path) == held:
        return None
    return max(0, size - _guard_tree_bytes(path))


def _guard_log_backups(base_dir):
    """(mtime, path, size) for the rolled backups of the runner's
    logs, oldest first. A rolled backup is pure history: it is the
    first material the guard gives up."""
    out = []
    for name in _DISK_GUARD_LOG_NAMES:
        try:
            entries = os.listdir(base_dir)
        except OSError:
            return out
        for entry in entries:
            if not entry.startswith(name + "."):
                continue
            path = os.path.join(base_dir, entry)
            try:
                st = os.lstat(path)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                continue
            out.append((st.st_mtime, path, st.st_size))
    out.sort()
    return out


def guard_disk(cfg, base_dir, now=None):
    """Run one disk guard pass over the runner's own material.

    Returns the annotation event when the pass truncated or
    removed anything, else None. The event names every action (up
    to a cap) and the bytes freed; the caller records it in
    security-events.jsonl. Never raises, and never stops the
    runner: a pass that cannot get the disk back under the
    threshold says so in its event (still_over), and the next pass
    is held off for the resources cooldown, so a disk the runner
    cannot fix does not earn an event on every poll.
    """
    try:
        now = float(time.time() if now is None else now)
    except (TypeError, ValueError):
        now = time.time()
    if not isinstance(base_dir, str) or not base_dir:
        return None
    if not disk_guard_enabled(cfg):
        return None
    before = _disk_fraction(base_dir)
    if before is None or before < DISK_GUARD_THRESHOLD:
        return None
    try:
        cooldown = parse_resources(cfg)["cooldown_sec"]
    except (RuntimeError, AttributeError, TypeError):
        cooldown = 900
    state = _load_state(base_dir)
    guard_state = state.get("disk_guard")
    if isinstance(guard_state, dict) and guard_state.get("still_over"):
        try:
            last = float(guard_state.get("at_epoch", 0) or 0)
        except (TypeError, ValueError):
            last = 0.0
        if now - last < cooldown:
            return None

    actions = []
    freed = 0

    def note(path, action, nbytes):
        nonlocal freed
        freed += nbytes
        if len(actions) < DISK_GUARD_MAX_ACTIONS:
            actions.append({
                "path": os.path.relpath(path, base_dir),
                "action": action, "bytes": nbytes})

    blind = False

    def under():
        # True when the pass gives up nothing more: the disk
        # measures under the threshold, or it cannot be measured.
        # Nothing is given up without a measurement that says the
        # disk is at or over the threshold, so a measurement that
        # fails ends the pass, and no later one is asked for.
        nonlocal blind
        if blind:
            return True
        frac = _disk_fraction(base_dir)
        if frac is None:
            blind = True
            return True
        return frac < DISK_GUARD_THRESHOLD

    # Stage 1: the logs. Rolled backups go first, oldest first;
    # then the live logs give up their oldest lines, keeping the
    # newest tail.
    for _mtime, path, _size in _guard_log_backups(base_dir):
        if under():
            break
        n = _guard_remove_file(path)
        if n is not None:
            note(path, "remove", n)
    if not under():
        for name in _DISK_GUARD_LOG_NAMES:
            if under():
                break
            path = os.path.join(base_dir, name)
            n = _guard_truncate_log(path, DISK_GUARD_LOG_KEEP_BYTES)
            if n:
                note(path, "truncate", n)
    # Stage 2: recorded results, retained outputs and given up
    # stashes, oldest first across all three. A recorded result
    # still inside the replay window is not material: it stays.
    if not under():
        old = []
        window = _guard_replay_window(cfg)
        for sub in _DISK_GUARD_OLD_DIRS:
            found = _guard_oldest_files(os.path.join(base_dir, sub))
            if sub == "sent":
                found = [item for item in found
                         if now - item[0] > window]
            old.extend(found)
        old.sort()
        for _mtime, path, _size in old:
            if under():
                break
            n = _guard_remove_file(path)
            if n is not None:
                note(path, "remove", n)
    # Stage 3: leftover job workspaces old enough that no job can
    # still be running in them.
    if not under():
        for _mtime, path, _size in _guard_oldest_workspaces(base_dir, now):
            if under():
                break
            n = _guard_remove_tree(path)
            if n is not None:
                note(path, "remove", n)

    after = _disk_fraction(base_dir)
    still_over = after is None or after >= DISK_GUARD_THRESHOLD
    state["disk_guard"] = {"at": _now_iso(), "at_epoch": now,
                           "freed_bytes": freed, "still_over": still_over}
    _save_state(base_dir, state)
    if not actions:
        return None
    return {
        "type": "disk_truncation",
        "at": _now_iso(),
        "threshold": DISK_GUARD_THRESHOLD,
        "disk_before": round(before, 4),
        "disk_after": round(after, 4) if after is not None else None,
        "freed_bytes": freed,
        "actions": actions,
        "still_over": still_over,
    }
