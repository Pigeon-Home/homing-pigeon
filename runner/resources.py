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
    try:
        threshold = float(raw.get("threshold", 0.95))
    except (TypeError, ValueError):
        raise RuntimeError("config error: resources.threshold must be a number")
    if not 0 < threshold <= 1:
        raise RuntimeError("config error: resources.threshold must be in (0, 1]")
    try:
        cooldown = float(raw.get("cooldown_sec", 900))
    except (TypeError, ValueError):
        raise RuntimeError("config error: resources.cooldown_sec must be a number")
    if (cooldown != cooldown or cooldown < 0 or cooldown == float("inf")
            or cooldown == float("-inf")):
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
    try:
        with open(os.path.join(base_dir, STATE_FILE), "r",
                  encoding="utf-8") as f:
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
    tmp = os.path.join(base_dir, STATE_FILE + ".tmp." + str(threading.get_ident()))
    try:
        with _STATE_LOCK:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(clean, f)
            os.replace(tmp, os.path.join(base_dir, STATE_FILE))
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
