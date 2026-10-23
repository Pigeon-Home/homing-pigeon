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
"""
import json
import os
import shutil
import threading
import time

try:
    from runner import confval as _confval
except ImportError:
    import confval as _confval  # type: ignore
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
    tmp = path + ".tmp." + str(threading.get_ident())
    fd = None
    try:
        with _STATE_LOCK:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            fd = os.open(tmp, flags, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                fd = None
                json.dump(clean, f)
            os.replace(tmp, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
    except (OSError, TypeError, ValueError):
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(tmp)
        except OSError:
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
