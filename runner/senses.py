#!/usr/bin/env python3
"""Oracle senses: inbound signal extensions (host IDS, network monitor).

A sense is a named signal source that files signed alerts with the
Oracle. Each sense is adjustable from day one: an enable flag, a
weight (how much the Oracle weighs its alerts), and a free-form
profile of tunables. The runner enforces a small set of known profile
knobs; unknown keys are accepted and carried through so future
heuristics can be tuned without a code change.

Alerts arrive as signed jobs of kind "sensor_alert" from a key bound
to the sense (see key_policies: allowed_kinds ["sensor_alert"]). They
are validated, gated by the sense profile, stored, and never
executed. The "senses" query op reads them back, ranked by
weight x severity.

This module is deliberately free of runner imports: the crypto and
mail flow stay in runner.py, which calls in here.
"""
import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

SEVERITY_SCORES = {
    "critical": 4.0,
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
    "info": 0.5,
}

SENSES_FILE = "senses.jsonl"


def _finite_number(value, default, lo=None):
    """A finite int or float from a stored value, else ``default``.

    A boolean is never a number here (``True`` is ``1`` to float()),
    nor is infinity, NaN, an integer too large for a float, a
    non-numeric string, or anything under ``lo``. The one place in
    this module that decides what a profile number means; kept local
    so senses.py stays free of runner imports.
    """
    if isinstance(value, bool):
        return default
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return default
    if not isinstance(value, (int, float)):
        return default
    try:
        f = float(value)
    except (OverflowError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    if lo is not None and f < lo:
        return default
    return value
MAX_STORED = 5000


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        return None
    return dt


def parse_sensors(cfg) -> dict:
    """Validate cfg["sensors"]. Returns {name: cleaned config}.

    Raises RuntimeError on config error, mirroring build_key_policies.
    Unknown profile keys are kept: the profile is the operator's
    tuning surface for heuristics that do not exist yet.
    """
    if not isinstance(cfg, dict):
        raise RuntimeError("config error: config must be an object")
    raw = cfg.get("sensors") or {}
    if not isinstance(raw, dict):
        raise RuntimeError("config error: sensors must be an object")
    out = {}
    for name, scfg in raw.items():
        where = f"config error: sensors[{name!r}]"
        if not isinstance(name, str) or not name:
            raise RuntimeError("config error: sensor names must be strings")
        if not isinstance(scfg, dict):
            raise RuntimeError(where + " must be an object")
        enabled = scfg.get("enabled", False)
        if not isinstance(enabled, bool):
            raise RuntimeError(where + ".enabled must be a boolean")
        key_id = scfg.get("key_id") or ""
        if not isinstance(key_id, str) or not key_id:
            raise RuntimeError(where + ".key_id must be a non-empty string")
        try:
            weight = float(scfg.get("weight", 1.0))
        except (TypeError, ValueError, OverflowError):
            raise RuntimeError(where + ".weight must be a number")
        if weight != weight or weight < 0 or weight == float("inf"):
            raise RuntimeError(where + ".weight must be a finite number >= 0")
        profile = scfg.get("profile") or {}
        if not isinstance(profile, dict):
            raise RuntimeError(where + ".profile must be an object")
        clean_profile = dict(profile)
        floor = clean_profile.get("severity_floor", "info")
        if not isinstance(floor, str) or floor not in SEVERITY_SCORES:
            raise RuntimeError(
                where + f".profile.severity_floor must be one of "
                f"{sorted(SEVERITY_SCORES)}")
        for knob in ("cooldown_sec", "max_per_hour"):
            if knob in clean_profile:
                try:
                    v = float(clean_profile[knob])
                except (TypeError, ValueError, OverflowError):
                    raise RuntimeError(where + f".profile.{knob} must be a number")
                if v != v or v < 0 or v == float("inf"):
                    raise RuntimeError(
                        where + f".profile.{knob} must be a finite number >= 0")
                clean_profile[knob] = v
        out[name] = {
            "enabled": enabled,
            "key_id": key_id,
            "weight": weight,
            "profile": clean_profile,
        }
    # Two senses may not share a key: the key binds the daemon's identity.
    seen_keys = {}
    for name, scfg in out.items():
        kid = scfg["key_id"]
        if kid in seen_keys:
            raise RuntimeError(
                f"config error: key_id {kid!r} is bound to both "
                f"sensors[{seen_keys[kid]!r}] and sensors[{name!r}]")
        seen_keys[kid] = name
    return out


def sensor_for_key(sensors: dict, key_id: str):
    """Return the sensor name bound to key_id, or None.

    A non-dict map or a non-dict entry is bad extension data. Return
    None rather than raise, so a poisoned sensors config cannot abort
    alert ingest.
    """
    if not isinstance(sensors, dict):
        return None
    for name, scfg in sensors.items():
        if not isinstance(scfg, dict):
            continue
        if scfg.get("key_id") == key_id:
            return name
    return None


def validate_sensor_alert(job: dict):
    """Shape-check a kind=sensor_alert job. Returns None or a reason."""
    if not isinstance(job, dict):
        return "job must be an object"
    sensor = job.get("sensor")
    if not isinstance(sensor, str) or not sensor:
        return "sensor must be a non-empty string"
    severity = job.get("severity") or "info"
    if not isinstance(severity, str) or severity not in SEVERITY_SCORES:
        return f"severity must be one of {sorted(SEVERITY_SCORES)}"
    title = job.get("title")
    if not isinstance(title, str) or not title.strip():
        return "title must be a non-empty string"
    if "detail" in job and not isinstance(job["detail"], dict):
        return "detail must be an object"
    if "observed_at" in job and job["observed_at"] is not None \
            and _parse_ts(job["observed_at"]) is None:
        return "observed_at must be a UTC ISO timestamp"
    if "job_id_hint" in job and job["job_id_hint"] is not None \
            and not isinstance(job["job_id_hint"], str):
        return "job_id_hint must be a string"
    if "signal" in job and job["signal"] is not None \
            and (not isinstance(job["signal"], str)
                 or not job["signal"].strip()):
        return "signal must be a non-empty string"
    return None


def gate_alert(sensor_cfg: dict, alert: dict, recent: list,
             now: Optional[float] = None):
    """Apply the sense profile's ingest gates.

    Returns None if the alert is kept, else a drop reason. `recent`
    is the sense's recent stored alerts (newest last), used for the
    cooldown and hourly cap.
    """
    try:
        now = float(time.time() if now is None else now)
    except (TypeError, ValueError):
        now = time.time()
    if not isinstance(sensor_cfg, dict):
        return "bad sensor config"
    if not isinstance(alert, dict):
        return "bad alert"
    if not isinstance(recent, list):
        recent = []
    profile = sensor_cfg.get("profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    floor = profile.get("severity_floor", "info")
    # A floor or severity that cannot be hashed is not a known level.
    try:
        if floor not in SEVERITY_SCORES:
            floor = "info"
    except Exception:
        floor = "info"
    sev = alert.get("severity", "info")
    try:
        if sev not in SEVERITY_SCORES:
            sev = "info"
    except Exception:
        sev = "info"
    if SEVERITY_SCORES[sev] < SEVERITY_SCORES[floor]:
        return f"below severity_floor {floor}"
    # docs/senses.md: cooldown_sec default 0 (no dedup). A boolean
    # is not a window: true once dropped every repeat within a second.
    cooldown = float(_finite_number(profile.get("cooldown_sec"), 0, lo=0))
    if cooldown > 0:
        for prev in reversed(recent):
            if not isinstance(prev, dict):
                continue
            pts = _parse_ts(prev.get("received_at"))
            if pts is None:
                continue
            if now - pts.timestamp() > cooldown:
                break
            if prev.get("title") == alert.get("title"):
                return f"cooldown: same title within {cooldown:g}s"
    # docs/senses.md: max_per_hour default 0 (unlimited). A boolean is
    # not a cap: true once allowed one alert an hour. A number that
    # is negative or non-finite stays the loud refusal it was.
    raw_cap = profile.get("max_per_hour")
    if isinstance(raw_cap, bool) or raw_cap is None:
        cap = 0.0
    else:
        try:
            cap = float(raw_cap)
        except (TypeError, ValueError, OverflowError):
            cap = 0.0
        if cap != cap or cap < 0 or cap in (float("inf"), float("-inf")):
            return "over max_per_hour (unreadable cap)"
    if cap > 0:
        n = 0
        for prev in reversed(recent):
            if not isinstance(prev, dict):
                continue
            pts = _parse_ts(prev.get("received_at"))
            if pts is None:
                continue
            if now - pts.timestamp() > 3600:
                break
            n += 1
        if n >= cap:
            return f"over max_per_hour {cap:g}"
    return None


def file_sensor_alert(base_dir, sensor_cfg, record):
    """Store one alert if the profile allows it. Returns a drop reason or None.

    The load, the gate, and the write are one step, so two workers
    cannot both pass the last slot of max_per_hour.
    """
    if not isinstance(base_dir, str) or not base_dir:
        return "bad base dir"
    if not isinstance(record, dict):
        return "bad alert"
    with _STORE_LOCK:
        try:
            recent = load_alerts(base_dir, sensor=record.get("sensor"), limit=500)
        except Exception:
            recent = []
        try:
            drop = gate_alert(sensor_cfg, record, recent)
        except Exception as e:
            return f"gate failed: {e}"
        if drop:
            return drop
        err = _store_alert_report(base_dir, record)
        if err is not None:
            # Missing directory or unwritable store must not abort ingest.
            return f"store failed: {err}"
        return None


def _path(base_dir: str) -> str:
    if not isinstance(base_dir, str) or not base_dir:
        return ""
    return os.path.join(base_dir, SENSES_FILE)


_STORE_LOCK = threading.RLock()


def _read_lines(path: str):
    """Text lines, or None when the path is a symlink or cannot be read.

    A symlink is not followed.
    """
    if not path or os.path.islink(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def _write_private(path: str, data: bytes, append: bool) -> None:
    """Write bytes without following a symlink. The file is mode 0600."""
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def store_alert(base_dir: str, record: dict) -> None:
    """Append one alert record; keep the file capped at MAX_STORED lines.

    Concurrent senses must not tear a line or drop each other's alerts.
    Never raises: a failed store is silent here. Callers that need to
    know (file_sensor_alert) use _store_alert_report.
    """
    _store_alert_report(base_dir, record)


def _store_alert_report(base_dir: str, record: dict):
    """store_alert's body. Returns the OSError a store hit, else None."""
    if not isinstance(base_dir, str) or not base_dir:
        return None
    if not isinstance(record, dict):
        return
    try:
        try:
            from runner.runner import _json_safe
        except ImportError:
            def _json_safe(v):
                return v
        line = json.dumps(_json_safe(record), ensure_ascii=False, allow_nan=False) + "\n"
    except (TypeError, ValueError):
        return
    path = _path(base_dir)
    with _STORE_LOCK:
        try:
            _write_private(path, line.encode("utf-8"), True)
            lines = _read_lines(path)
            if not lines or len(lines) <= MAX_STORED:
                return
            body = "".join(lines[-MAX_STORED:]).encode("utf-8")
            _write_private(path, body, False)
        except OSError as e:
            return e
    return None


def load_alerts(base_dir: str, sensor=None, severity_floor=None,
                since=None, until=None, limit=50):
    """Read stored alerts, oldest first, with optional filters."""
    if not isinstance(base_dir, str) or not base_dir:
        return []
    path = _path(base_dir)
    with _STORE_LOCK:
        try:
            lines = _read_lines(path)
            if lines is None:
                return []
        except (OSError, UnicodeDecodeError):
            # Corrupt or non-UTF-8 store must not crash the poll or query path.
            return []
    since_dt = _parse_ts(since) if since else None
    until_dt = _parse_ts(until) if until else None
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        if sensor:
            try:
                same = rec.get("sensor") == sensor
            except Exception:
                same = False
            if not same:
                continue
        if severity_floor is not None:
            # docs/senses.md, "Alert format": a missing severity is
            # info. An alert stored with no severity (or null) is read
            # back as info, so the default floor "info (keep all)"
            # keeps it instead of dropping it below the floor.
            try:
                sev = rec.get("severity")
                if not isinstance(sev, str) or sev not in SEVERITY_SCORES:
                    sev = "info"
                if SEVERITY_SCORES[sev] < SEVERITY_SCORES.get(severity_floor, 0):
                    continue
            except Exception:
                continue
        ts = _parse_ts(rec.get("observed_at") or rec.get("received_at"))
        if since_dt and (ts is None or ts < since_dt):
            continue
        if until_dt and (ts is None or ts > until_dt):
            continue
        out.append(rec)
    if limit is not None:
        try:
            n = int(limit)
        except (TypeError, ValueError, OverflowError):
            n = 50
        if n < 0:
            n = 0
        out = out[-n:]
    return out


def alert_score(alert: dict, weight: float) -> float:
    """How much the Oracle weighs this alert: source weight x severity.

    docs/senses.md: weight default 1.0. A weight that is negative,
    infinite, NaN, a boolean, a non-number, or an integer too large
    for a float is not a weight and scores as 1.0 (a huge integer
    once raised OverflowError out of here).
    """
    weight_n = float(_finite_number(weight, 1.0, lo=0))
    severity = alert.get("severity") if isinstance(alert, dict) else None
    score = SEVERITY_SCORES.get(severity, 0.5) if isinstance(severity, str) else 0.5
    return weight_n * score


# ---------------------------------------------------------------------------
# Optional low-overhead detection (rules, plan budgets, baseline)
# ---------------------------------------------------------------------------
# The runner evaluates runner/detection.py after job completion and
# records advisory fields on the result (detection_hits,
# detection_anomaly, plan_budget_ok). Canary tripwires are separate:
# they live in runner._canary_watch. This module stays free of heavy
# imports; the note exists so the two systems are not confused.
